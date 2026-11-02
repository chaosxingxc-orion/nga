#!/usr/bin/env python3
"""Config-only BEV DEV package reuse and asynchronous NPU/CPU activation.

Trusted reviewed templates only. No model/protocol changes or review inheritance.
Run on the analysis host with shared CephFS and the fixed `npu` SSH alias.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

SPEC = importlib.util.spec_from_file_location('entry', Path(__file__).with_name('experiment_entrypoint.py'))
E = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(E)
SCHEMA = 'nga-bev-workflow-prepare-v1'
ACTIVATION = 'nga-bev-workflow-activation-v1'


def pin(path):
    path = E.safe(str(path)); return {'path': str(path), 'sha256': E.digest(path)}


def write(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def frozen(path, expected):
    return E.read_json(E.pinned({'path': str(path), 'sha256': expected}))


def prepare(path, expected):
    c = frozen(path, expected)
    if c.get('schema') == 'nga-bev-public-test-prepare-v1':
        return module(Path(__file__).with_name('bev_public_test_builder.py'), 'bev_public_builder').prepare(path, expected)
    E.require(set(c) == {'schema', 'template_plan', 'template_cpu', 'root', 'run', 'container', 'chip'}, 'prepare fields differ')
    E.require(c['schema'] == SCHEMA, 'unsupported prepare schema')
    E.require(type(c['chip']) is int and 0 <= c['chip'] < 8, 'chip must be integer 0..7')
    E.require(re.fullmatch(r'r3_runs/[a-zA-Z0-9_-]+', c['run']), 'invalid run')
    E.require(re.fullmatch(r'nga-[a-zA-Z0-9_-]+', c['container']), 'invalid container')
    root = E.safe(c['root']); E.require(not root.exists(), 'output already exists')
    E.require(c['run'] == 'r3_runs/' + root.name, 'run must match new root name')
    tp = E.pinned(c['template_plan']); plan = E.read_json(tp)
    tc = E.pinned(c['template_cpu']); cpu = E.read_json(tc)
    E.require(plan['schema'] == 'bev-dev-plan-v1' and plan['source_split'] == 'train_derived_dev'
              and plan['scientific_acceptance'] is False and plan['test_read'] is False, 'template scope differs')
    E.require(c['run'] != plan.get('run') and c['container'] != plan.get('container'), 'new instance identity required')
    E.require(cpu['plan'] == str(tp) and cpu['plan_sha256'] == E.digest(tp), 'template CPU/plan differs')
    for group in ('code', 'inputs', 'model_files'):
        for item in plan[group].values(): E.pinned(item)
    for name, h in cpu['files'].items(): E.pinned({'path': name, 'sha256': h})
    source_consumer = tc.parent / 'consume.py'
    E.require(cpu['files'].get(str(source_consumer)) == E.digest(source_consumer), 'consumer not pinned')
    source_prereg = tp.parent / 'PREREGISTRATION.md'
    E.require(cpu['files'].get(str(source_prereg)) == E.digest(source_prereg), 'protocol not pinned')
    runner = module(plan['code']['runner']['path'], 'bev_template_runner')
    runner.verify(tp, E.digest(tp))
    consumer = module(source_consumer, 'bev_template_consumer')
    consumer.verify_config(tc, E.digest(tc))
    # Reserving the root is the transaction boundary. Failed preparation remains
    # inspectable and is never overwritten or admitted as a completed package.
    root.mkdir(parents=False)
    try:
        inf = root / 'inference'; analysis = root / 'cpu'; control = root / 'control'
        for folder in (inf, analysis, control, inf/'code', inf/'inputs', inf/'output'): folder.mkdir()
        for group in ('code', 'inputs'):
            names = set()
            for name, item in plan[group].items():
                source = E.pinned(item); E.require(source.name not in names, 'duplicate copied basename')
                names.add(source.name); target = inf/group/source.name
                shutil.copyfile(source, target); plan[group][name] = pin(target)
        plan.update(run=c['run'], container=c['container'], chip=c['chip'], out=str(inf/'output'))
        plan['mounts'] = [dict(source=str(inf), destination=str(inf), readonly=True),
                          dict(source=str(inf/'output'), destination=str(inf/'output'), readonly=False),
                          dict(source=plan['model'], destination=plan['model'], readonly=True)]
        pp = inf/'plan.json'; write(pp, plan)
        shutil.copyfile(source_prereg, inf/'PREREGISTRATION.md')
        shutil.copyfile(source_consumer, analysis/'consume.py')
        cpu.update(plan=str(pp), plan_sha256=E.digest(pp))
        refs = [analysis/'consume.py', pp, E.safe(cpu['gold']), E.pinned(plan['source_manifest']), inf/'PREREGISTRATION.md']
        cpu['files'] = {str(x): E.digest(x) for x in refs}
        for group in ('code', 'inputs'):
            cpu['files'].update({x['path']: x['sha256'] for x in plan[group].values()})
        cp = analysis/'config.json'; write(cp, cpu)
        module(plan['code']['runner']['path'], 'bev_new_runner').verify(pp, E.digest(pp))
        newconsumer = module(analysis/'consume.py', 'bev_new_consumer'); newconsumer.verify_config(cp, E.digest(cp))
        requests = [json.loads(x) for x in E.safe(plan['inputs']['requests']['path']).read_text().splitlines()]
        gold = [json.loads(x) for x in E.safe(cpu['gold']).read_text().splitlines()]
        newconsumer.population(requests, gold, 6516)
        E.require([r['id'] for r in requests] == E.read_json(E.safe(plan['inputs']['ids']['path'])), 'ordered IDs differ')
        receipt = dict(schema='nga-bev-workflow-prepared-v1', config=pin(path), template_plan=c['template_plan'],
                       template_cpu=c['template_cpu'], plan=pin(pp), cpu=pin(cp), consumer=pin(analysis/'consume.py'),
                       entrypoint=pin(Path(E.__file__)), workflow=pin(Path(__file__)),
                       approved=False, scientific_acceptance=False, test_read=False)
        write(root/'PREPARED.json', receipt)
        write(control/'RELAUNCH.json', {'note': 'Bind a NEW independent review to these exact plan and CPU hashes, then use activation config. No template authorization is inherited.', 'plan': pin(pp), 'cpu': pin(cp)})
        return {'status': 'prepared_requires_new_review', 'prepared': pin(root/'PREPARED.json')}
    except Exception as error:
        write(root/'PREPARE_FAILED.json', {'error': str(error), 'exit_code': 1}); raise


def bind(prepared_path, prepared_sha, review_path, review_sha, attempt):
    p = frozen(prepared_path, prepared_sha); root = E.safe(str(prepared_path)).parent
    public = p.get('schema') == 'nga-bev-public-test-prepared-v1'
    E.require(p['schema'] in ('nga-bev-workflow-prepared-v1', 'nga-bev-public-test-prepared-v1')
              and p['approved'] is False, 'prepared schema differs')
    for key in ('plan', 'cpu', 'consumer', 'entrypoint', 'workflow'): E.pinned(p[key])
    E.require(p['entrypoint'] == pin(Path(E.__file__)) and p['workflow'] == pin(Path(__file__)), 'workflow version differs')
    review = frozen(review_path, review_sha)
    E.require(review.get('deployment_suitable') is True and review.get('cpu_config_sha256') == p['cpu']['sha256']
              and review.get('consumer_sha256') == p['consumer']['sha256'], 'CPU admission differs')
    if public:
        module(p['consumer']['path'], 'bev_public_consumer_bind').verify_config(p['cpu']['path'], p['cpu']['sha256'])
    entry = dict(schema=E.SCHEMA, kind='bev-public-test-v1' if public else 'bev-dev-v1', plan=p['plan'],
                 review={'path': str(E.safe(str(review_path))), 'sha256': review_sha}, attempt=attempt)
    # Validate in our own temporary directory before reserving the final attempt.
    # A rejected review must not prevent a corrected review for the same attempt.
    # TemporaryDirectory only removes this invocation's staging files; an existing
    # final attempt is never removed or overwritten.
    with tempfile.TemporaryDirectory(prefix='.bind-', dir=root/'control') as staging:
        staged_entry = Path(staging)/'entry.json'; write(staged_entry, entry)
        E.load_config(staged_entry, E.digest(staged_entry))
        destination = root/'control'/('attempt-'+str(attempt)); destination.mkdir()
        ep = destination/'entry.json'; write(ep, entry)
    activation = dict(schema=ACTIVATION, entry=pin(ep), cpu=p['cpu'], consumer=p['consumer'],
                      prepared={'path': str(prepared_path), 'sha256': prepared_sha},
                      workflow=pin(Path(__file__)), entrypoint=pin(Path(E.__file__)), ssh_host='npu')
    ap = destination/'activation.json'; write(ap, activation)
    return {'status': 'bound', 'activation': pin(ap)}


def load_activation(path, expected):
    c = frozen(path, expected)
    E.require(set(c) == {'schema','entry','cpu','consumer','prepared','workflow','entrypoint','ssh_host'} and
              c['schema'] == ACTIVATION and c['ssh_host'] == 'npu', 'activation fields differ')
    for key in ('entry','cpu','consumer','prepared','workflow','entrypoint'): E.pinned(c[key])
    E.require(c['workflow'] == pin(Path(__file__)) and c['entrypoint'] == pin(Path(E.__file__)), 'tool version differs')
    p = E.read_json(E.pinned(c['prepared']))
    E.require(c['cpu'] == p['cpu'] and c['consumer'] == p['consumer'], 'prepared CPU binding differs')
    entry, plan = E.load_config(c['entry']['path'], c['entry']['sha256'])
    E.require(entry['plan'] == p['plan'], 'prepared plan binding differs')
    review = E.read_json(E.pinned(entry['review']))
    E.require(review.get('deployment_suitable') is True and review.get('cpu_config_sha256') == c['cpu']['sha256']
              and review.get('consumer_sha256') == c['consumer']['sha256'], 'CPU review differs')
    consumer = module(c['consumer']['path'], 'bev_consumer_validate')
    consumer.verify_config(c['cpu']['path'], c['cpu']['sha256'])
    return c, entry, plan


def cpu_start(c):
    root = E.safe(c['cpu']['path']).parent
    cmd = [sys.executable, '-B', '-P', c['consumer']['path'], '--config', c['cpu']['path'], '--sha256', c['cpu']['sha256']]
    with (root/'workflow-start.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (root/'EXIT.json').exists():
            end = E.read_json(root/'EXIT.json')
            E.require(end.get('exit_code') == 0 and end.get('config_sha256') == c['cpu']['sha256']
                      and E.digest(root/'report.json') == end.get('report_sha256'), 'CPU terminal requires reconciliation')
            return {'status': 'already_complete'}
        if (root/'SERVICE.json').exists():
            service = E.read_json(root/'SERVICE.json'); pid = service['pid']
            E.require(service['command'] == cmd and type(pid) is int, 'CPU service identity differs')
            actual = Path('/proc')/str(pid)/'cmdline'
            E.require(actual.exists() and actual.read_bytes().split(b'\0')[:-1] == [x.encode() for x in cmd],
                      'CPU service uncertain; reconcile before restart')
            return {'status': 'already_running', 'pid': pid}
        E.require(not (root/'START_INTENT.json').exists(), 'CPU start intent needs reconciliation')
        write(root/'START_INTENT.json', {'command':cmd,'utc_seconds':time.time()})
        write(root/'RELAUNCH.json', {'command':cmd,'environment':{'PYTHONDONTWRITEBYTECODE':'1'},
                                    'note':'Use workflow start-cpu with original activation; failed or uncertain receipts require reconciliation.'})
        with (root/'consumer.log').open('ab') as log:
            worker = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                      start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        write(root/'SERVICE.json', {'command':cmd,'pid':worker.pid,'config_sha256':c['cpu']['sha256']})
        return {'status':'consumer_started','pid':worker.pid}


def operate(op, path, expected):
    candidate = frozen(path, expected)
    if candidate.get('schema') == 'nga-bev-public-test-prepared-v1':
        E.require(op in ('validate','dry-run'), 'prepared package requires independent review and bind before activation')
        return module(Path(__file__).with_name('bev_public_test_builder.py'), 'bev_public_validate').validate_prepared(path, expected, op)
    c, entry, plan = load_activation(path, expected)
    if op == 'validate':
        return {'status':'validated','inference':E.execute('validate',c['entry']['path'],c['entry']['sha256'])}
    if op == 'status':
        cp = E.safe(c['cpu']['path']).parent
        return {'inference':E.status(entry,plan),'cpu':{n:E.read_json(cp/n) for n in ('digest.json','EXIT.json','SERVICE.json') if (cp/n).exists()},
                'note':'Structured receipts only; no live/full-success inference.'}
    remote = ['/usr/bin/python3.12','-B','-P',plan['code']['host']['path'],'start',
              '--plan',entry['plan']['path'],'--sha256',entry['plan']['sha256'],
              '--review',entry['review']['path'],'--review-sha256',entry['review']['sha256'],
              '--attempt',str(entry['attempt'])]
    if op == 'dry-run': return {'status':'validated_dry_run','npu_command':['ssh','npu',shlex.join(remote)],'cpu_config':c['cpu'],'writes_performed':False}
    if op == 'start-cpu': return cpu_start(c)
    E.require(op == 'start', 'unsupported operation')
    E.require(not (E.safe(plan['out'])/'host_attempts'/str(entry['attempt'])).exists(), 'attempt already exists; inspect status; use start-cpu only for missing CPU handoff')
    E.execute('validate', c['entry']['path'], c['entry']['sha256'])
    result = subprocess.run(['ssh','npu',shlex.join(remote)],capture_output=True,text=True,timeout=180)
    E.require(result.returncode == 0, 'NPU start failed/uncertain; inspect receipts before retry: '+result.stderr[-1000:])
    # The existing supervisor is detached. CPU scoring waits for its full terminal.
    return {'status':'npu_start_returned','inference':result.stdout[-1500:],'cpu':cpu_start(c)}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('op',choices=['prepare','bind','validate','dry-run','start','start-cpu','status'])
    ap.add_argument('--config',required=True); ap.add_argument('--sha256',required=True)
    ap.add_argument('--review');ap.add_argument('--review-sha256');ap.add_argument('--attempt',type=int,default=1)
    a=ap.parse_args(argv)
    try:
        if a.op=='prepare': result=prepare(a.config,a.sha256)
        elif a.op=='bind':
            E.require(a.review is not None and a.review_sha256 is not None,'new independent review required')
            result=bind(a.config,a.sha256,a.review,a.review_sha256,a.attempt)
        else: result=operate(a.op,a.config,a.sha256)
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps({'status':'rejected','error':str(error)},ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
