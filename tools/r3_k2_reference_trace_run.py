"""Pinned two-reference diagnostic, never a speed or numerical admission run."""
import argparse
import json
from pathlib import Path
import types


def local_source(name):
    path = Path(__file__).resolve().with_name(name+'.py')
    module = types.ModuleType(name); module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


B = local_source('r3_k2_sync_benchmark')
TRACE = local_source('r3_k2_reference_trace')
ReferenceTrace, instrument = TRACE.ReferenceTrace, TRACE.instrument

PROTOCOL = {'seed': 2, 'step': 0, 'reference_evaluations': 2,
            'max_questions': 32, 'max_reference_bytes': 2 * 1024**3,
            'chips': 1, 'diagnostic_only': True}
BOUNDARY_PROTOCOL = dict(PROTOCOL, reference_evaluations=4,
                         boundary_observers=True, control_reference_evaluations=2)


def run(path, pin):
    B.require(B.sha(path) == pin, 'trace plan changed')
    plan = json.loads(Path(path).read_text())
    boundary = plan['schema'] == 'r3-k2-reference-trace-plan-v2'
    B.require(plan['schema'] in ('r3-k2-reference-trace-plan-v1','r3-k2-reference-trace-plan-v2')
              and plan['protocol'] == (BOUNDARY_PROTOCOL if boundary else PROTOCOL)
              and plan['test_read'] is False and plan['scientific_acceptance'] is False, 'trace scope differs')
    for filename, expected in plan['files'].items():
        p = Path(filename)
        B.require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe input')
        B.require(not any(x == 'test' or x.startswith('test.') for x in p.parts), 'test input forbidden')
        B.require(B.sha(p) == expected, 'trace input changed')
    B.require(plan['files'].get(str(Path(__file__).resolve())) == B.sha(__file__), 'runner not pinned')
    out = Path(plan['out'])
    B.require(not out.exists(), 'fresh trace output required')
    out.mkdir()
    import torch
    import torch_npu  # noqa: F401
    import transformers
    trainer = B.source(plan['trainer'], 'trace_reference')
    B.require(trainer.file_sha256(trainer.TRAIN_FILE) == plan['files'][trainer.TRAIN_FILE], 'train input changed')
    args = trainer.parse_args(['--out', str(out), '--arm', 'k2', '--seed', '2', '--model-path', plan['model'],
                              '--kernel', 'ref', '--grad-ckpt', '--micro-tokens', '12000', '--max-len', '4096',
                              '--expect-pairs', '186', '--no-merge'])
    tokenizer = transformers.AutoTokenizer.from_pretrained(args.model_path)
    data = trainer.Data(args)
    model, trainable, pairs = trainer.build_model(args, torch)
    model.to(args.device); model.train()
    trace = ReferenceTrace(torch, trainable, B.rng_snapshot, B.equality_diagnostic,
                           PROTOCOL['max_questions'], PROTOCOL['max_reference_bytes'])
    extra = None
    if boundary:
        boundary_module = local_source('r3_k2_boundary_trace')
        format_fn = getattr(torch_npu, 'get_npu_format', None)
        extra = boundary_module.BoundaryTrace(torch, trainable, backend_format=format_fn)
    def observe(*values):
        trace.observe(*values)
        if extra is not None and extra.handles:
            extra.after()
        B.atomic(out/'heartbeat.json', {'phase': trace.phase, 'completed_questions': trace.index,
                 'utc_seconds': B.time.time(), 'scientific_acceptance': False, 'test_read': False})
    fn = instrument(trainer, observe, trace.observe_chunk)
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
    endpoints = []
    control = None
    try:
        for pair in range(2 if boundary else 1):
            if pair:
                control = dict(trace.summary(), endpoints=endpoints)
                B.require(control['complete'], 'control incomplete')
                B.atomic(out/'CONTROL_TRACE.json', control)
                trace = ReferenceTrace(torch, trainable, B.rng_snapshot, B.equality_diagnostic,
                                       PROTOCOL['max_questions'], PROTOCOL['max_reference_bytes'])
                endpoints = []
                extra.install()
                fn = instrument(trainer, observe, trace.observe_chunk, extra.before, extra.reduction)
            for phase in range(2):
                if phase:
                    trace.begin_repeat()
                    if pair:
                        extra.begin_repeat()
                # Match the trainer's preamble; retain every example and denominator.
                units = data.step_units(0)[1]
                before = B.seed_and_snapshot(torch, 2, 0)
                model.zero_grad(set_to_none=True)
                loss, stats = fn(torch, model.base_model.model, tokenizer, units, 'k2', args.device,
                                 pad, 4096, 12000, {}, backward=True)
                endpoints.append({'loss': loss, 'stats': stats, 'rng_before': before, 'rng_after': B.rng_snapshot(torch)})
        result = dict(trace.summary(), plan_sha256=pin, endpoints=endpoints,
                      source_pins=plan['files'], instrumentation_sha256=plan['files'][str(Path(__file__).with_name('r3_k2_reference_trace.py'))])
        B.require(result['complete'], 'incomplete trace')
        B.require(result['reference_questions'] == sum(len(u) for u in units), 'question coverage differs')
        if boundary:
            result['boundary'] = extra.summary()
            B.require(result['boundary']['complete'] and result['boundary']['incoming_events'] > 0,
                      'boundary observations incomplete')
            result['control'] = control
            result['runtime'] = {name: {'version': getattr(mod, '__version__', None),
                'source_path': getattr(mod, '__file__', None),
                'source_sha256': B.sha(mod.__file__) if getattr(mod, '__file__', None) else None}
                for name, mod in [('torch', torch), ('torch_npu', torch_npu), ('transformers', transformers)]}
        B.atomic(out/'TRACE.json', result)
        return result
    finally:
        if extra is not None:
            extra.close()
            B.atomic(out/'BOUNDARY_PARTIAL.json', extra.summary())
        B.atomic(out/'TRACE_PARTIAL.json', dict(trace.summary(), plan_sha256=pin, endpoints=endpoints))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True); parser.add_argument('--sha256', required=True)
    args = parser.parse_args(); plan = json.loads(Path(args.plan).read_text()); rc = 1
    try:
        run(args.plan, args.sha256); rc = 0
    finally:
        out = Path(plan['out'])
        if out.exists():
            B.atomic(out/'EXIT.json', {'exit_code': rc, 'plan_sha256': args.sha256,
                                     'scientific_acceptance': False, 'test_read': False})
