#!/usr/bin/env python3
"""E40 NPU driver. No launcher or allocation mutation; exact reviewed plan required."""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import types


def bootstrap(plan_path, expected_sha):
    raw = plan_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('Caller-pinned plan SHA differs')
    p = json.loads(raw); out = plan_path.parent
    if p['out'] != str(out) or plan_path.is_symlink():
        raise ValueError('Plan location differs')
    # All E40/E38 helper imports execute only after this whole local closure is authenticated.
    for f in out.glob('*.py'):
        if f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest() != p['files'].get(str(f)):
            raise ValueError('Unbound executable: ' + str(f))
    def module(path, name):
        path = Path(path); data = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(data).hexdigest() != p['files'].get(str(path)):
            raise ValueError('Executable changed: ' + str(path))
        value = types.ModuleType(name); value.__file__ = str(path)
        exec(compile(data, str(path), 'exec'), value.__dict__)
        return value
    e = module(out/'e38_evidence.py', 'e40_evidence')
    bound = e.Evidence(); bound.frozen({k:v for k,v in p['files'].items() if k.endswith('.py')})
    return p, module, e, bound


@contextlib.contextmanager
def lifetime_path(backbone, torch, source, mode, expected_names, candidate, calls):
    replaced = []
    try:
        found = [(name, mod) for name, mod in backbone.named_modules()
                 if type(mod).__name__ == 'Qwen3_5GatedDeltaNet']
        if [n for n, _ in found] != expected_names or backbone.training:
            raise ValueError('Native model/core population or evaluation state differs')
        for name, mod in found:
            original = mod.chunk_gated_delta_rule
            if Path(inspect.getsourcefile(original)).read_bytes() != source:
                raise ValueError('Loaded native module source differs')
            selected = original if mode == 'original' else candidate.build_candidate(source, original, mode)
            signature = inspect.signature(original)
            def wrapper(*args, _name=name, _fn=selected, _sig=signature, **kwargs):
                call = _sig.bind(*args, **kwargs); call.apply_defaults()
                candidate.validate_call(torch, call)
                if list(call.arguments['query'].shape) != [15, 186, 16, 128]:
                    raise ValueError('Full-shape 2B GDN input differs')
                if call.arguments['query'].dtype != torch.bfloat16:
                    raise ValueError('Native GDN dtype differs')
                calls.append(_name)
                return _fn(*args, **kwargs)
            mod.chunk_gated_delta_rule = wrapper; replaced.append((mod, original))
        yield
        if calls != expected_names:
            raise ValueError('GDN call order/count differs')
    finally:
        for mod, original in replaced:
            mod.chunk_gated_delta_rule = original


def generation(q, e, p, ph, running=True):
    out = Path(p['out']); receipt = e.load(out/'LAUNCH_RECEIPT.json')
    spec = e.load(p['container_spec']); actual = q.inspect(p['container'])
    q.binding(actual, spec, receipt)
    if (receipt['plan_sha256'] != ph or receipt['wrapper_sha256'] != e.sha(p['wrapper'])
            or receipt['parent_review_sha256'] != e.sha(out/'PARENT_REVIEW.json')):
        raise ValueError('Launch receipt binding differs')
    for filename in ('PARENT_REVIEW.json', 'INDEPENDENT_REVIEW.json'):
        review = e.load(out/filename)
        if review.get('approved') is not True or review['approved_plan_sha256'] != ph:
            raise ValueError('Exact plan review absent')
        if filename == 'INDEPENDENT_REVIEW.json' and e.sha(review['review_path']) != review['review_sha256']:
            raise ValueError('Independent review bytes differ')
    if running:
        if (actual['State']['Status'] != 'running' or not Path('/.dockerenv').exists()
                or socket.gethostname() != actual['Config']['Hostname']):
            raise ValueError('Not executing in retained running Docker generation')
    return dict(container_id=actual['Id'], started_at=actual['State']['StartedAt'],
                launch_receipt_sha256=e.sha(out/'LAUNCH_RECEIPT.json')), actual


def run(path, ph):
    p, module, durable, bound = bootstrap(path, ph); out = path.parent
    proto = module(out/'openjev_lifetime_protocol.py', 'e40_protocol')
    proto.validate_plan(p)
    fd = os.open(out/'driver.lock', os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        durable.publication_gate(out)
        state = dict(stage='verify', progress=0, total=8, chips=1)
        stop = threading.Event(); rc = 1; error = None; report = None
        q = module(out/'jeval_reference_queue.py', 'e40_docker')
        def heartbeat():
            while not stop.wait(10):
                value = dict(utc=q.utc(), **state)
                q.atomic(out/'STATUS.json', value)
                (out/'digest.md').write_text(json.dumps(value)+'\n')
                with (out/'heartbeat.log').open('a') as stream: stream.write(json.dumps(value)+'\n')
        thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
        try:
            bound.frozen(p['files']); proto.require(bound.sha(path) == ph, 'Plan changed')
            gen, actual = generation(q, bound, p, ph)
            durable.publish_new(out/'GENERATION.json', gen)
            verifier = module(out/'openjev_lifetime_verify.py', 'e40_verifier')
            old = module(out/'verify_openjev_path_trace.py', 'e40_prediction_check')
            try: proto.check_receipts(p, ph, bound, old.check_prediction, generation=gen)
            except ValueError as exc:
                durable.fail_generation(out, str(exc)); raise
            c = bound.load(p['source_config'])
            proto.require(c['base_id'] == 'Qwen/Qwen3.5-2B', 'First stage is 2B only')
            native = module(Path(c['out'])/'jeval_reference_inference.py', 'e40_native')
            previous = module(out/'openjev_path_trace_run.py', 'e40_input')
            eligibility = native.verify_files(c)
            proto.require(previous.prepare_input(c, eligibility) == p['input'], 'Frozen native input differs')
            state['stage'] = 'load_model'; model = native.Native(c); torch = model.torch
            candidate = module(out/'openjev_lifetime_candidate.py', 'e40_candidate')
            source = bound.snapshot(p['native_source']).data
            proto.require(hashlib.sha256(source).hexdigest() == candidate.SOURCE_SHA256, 'Source changed')
            req = p['input']['request']; eligible = model.eligibility(req)
            proto.require(eligible == p['input']['eligibility'], 'Runtime eligibility differs')
            for folder in ('items', 'attempts'): durable.durable_mkdir(out/folder)
            for index, task in enumerate(proto.schedule()):
                key = proto.name(task); receipt = out/'items'/(key+'.json')
                state.update(stage=key, progress=index)
                if receipt.exists():
                    value = bound.load(receipt)['payload']
                else:
                    bound.verify(metadata_only=True)
                    current, _ = generation(q, bound, p, ph)
                    proto.require(current == gen, 'Container restarted')
                    torch.npu.empty_cache(); torch.npu.synchronize()
                    free_bytes, _ = torch.npu.mem_get_info()
                    proto.require(free_bytes / 2**30 >= p['safety']['min_free_gib'], 'Insufficient free memory before forward')
                    torch.npu.reset_peak_memory_stats()
                    baseline = dict(baseline_allocated_gib=torch.npu.memory_allocated()/2**30,
                                    baseline_reserved_gib=torch.npu.memory_reserved()/2**30,
                                    free_before_gib=free_bytes/2**30)
                    ident = proto.identity(p, ph, task); attempt = out/'attempts'/(key+'.json')
                    durable.publish_new(attempt, dict(**ident, generation=gen, phase='forward_intent', utc=q.utc()))
                    observed = {}; calls = []
                    with torch.inference_mode(), lifetime_path(model.model.backbone, torch, source, task['mode'],
                            p['expected_core_names'], candidate, calls):
                        start = time.monotonic()
                        with previous.input_guard(model.model.backbone, p['input'], observed):
                            prediction = model.predict(req, eligible)
                        torch.npu.synchronize(); seconds = time.monotonic()-start
                    value = dict(**ident, generation=gen, attempt_sha256=bound.sha(attempt), prediction=prediction,
                        observed_input=observed, core_calls=calls, candidate_source_sha256=p['candidate_sources'][task['mode']],
                        seconds=seconds, questions_per_second_per_chip=1/seconds,
                        tokens_per_second_per_chip=sum(eligible['lengths'])/seconds, chips=1, **baseline,
                        peak_allocated_gib=torch.npu.max_memory_allocated()/2**30,
                        peak_reserved_gib=torch.npu.max_memory_reserved()/2**30)
                    old.check_prediction(prediction, p); proto.check_metrics(value, p)
                    durable.publish_new(receipt, dict(payload=value, sha256=proto.stamp(value)))
                state.update(progress=index+1, questions_per_second_per_chip=value['questions_per_second_per_chip'],
                             tokens_per_second_per_chip=value['tokens_per_second_per_chip'], reserved_gib=value['peak_reserved_gib'])
            values = proto.check_receipts(p, ph, bound, old.check_prediction, complete=True, generation=gen)
            report = dict(plan_sha256=ph, generation=gen, **verifier.reconstruct(values),
                receipt_manifest={f.name:bound.sha(f) for f in sorted((out/'items').iterdir())},
                attempt_manifest={f.name:bound.sha(f) for f in sorted((out/'attempts').iterdir())})
            bound.verify(); durable.publish_new(out/'report.json', report)
            state['stage']='completed'; rc=0
        except BaseException as exc:
            error=type(exc).__name__+': '+str(exc); state['stage']='failed'; raise
        finally:
            stop.set(); thread.join()
            durable.publish_new(out/'COMPLETE.json', dict(rc=rc, error=error, plan_sha256=ph, **state,
                output_sha256=bound.sha(out/'report.json') if report is not None and (out/'report.json').exists() else None,
                candidate_batch_admission=False, utc=q.utc()))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True); args=parser.parse_args()
    run(args.plan.absolute(), args.plan_sha256)
