"""Bind model-specific scorer identity without relaxing common DEV protocol checks.

Version 2 training/DEV recovery and all numeric formulae are retained.
Only scorer.model_path/adapter are derived from pinned member and evaluation
identities. The caller still authenticates the complete campaign configuration.
"""
import copy
from pathlib import Path

# Load in an isolated module graph using the existing exact-source loader.
import hashlib
import types

def load(path, pin, name):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('qualification composition source changed: '+str(path))
    mod = types.ModuleType(name); mod.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), mod.__dict__)
    return mod

V = load(Path(__file__).with_name('r3_dev_qualification_recovery_v2.py'),
         'f4ecf4b4d7ac858c93d9dead95010d47584f7e5b559cf322617f9f518214d584',
         'recovered_qualification_v2')
Q = V.Q
_original_protocol = Q.protocol
_original_source_api = Q.source_api

def floor_views(original, repeats):
    """Separate authenticated adapter identity from cross-run protocol equality.

    Individual members have already passed exact pinned execution/spec identity.
    Recheck report self-consistency here, retain base identity and every scorer
    setting, and change only adapter path in private comparison views. No saved
    report, selection evidence, metric, recipe or threshold is changed.
    """
    reports = [original] + list(repeats.values())
    base = original['header']['model']
    for r in reports:
        h = r['header']; model = h['model']; scorer = h['scorer']
        Q.require(model['kind'] == 'lora-adapter-unmerged'
                  and scorer['model_path'] == model['base_path'] == base['base_path']
                  and model['base_revision'] == base['base_revision']
                  and scorer['adapter'] == model['path'] == r['selection_evidence']['adapter_path'],
                  'floor member scorer identity differs')
    paths = [r['header']['model']['path'] for r in reports]
    Q.require(len(set(paths)) == len(paths), 'floor member adapter reused')
    def view(r):
        h = dict(r['header']); s = dict(h['scorer'])
        s['adapter'] = original['header']['scorer']['adapter']; h['scorer'] = s
        return dict(r, header=h)
    return view(original), {role:view(r) for role,r in repeats.items()}

def source_api():
    api = _original_source_api()
    original_floor = api.Q.floor_diagnostics
    def floor_diagnostics(original, repeats, S, gates):
        first, others = floor_views(original, repeats)
        return original_floor(first, others, S, gates)
    # numeric resolves this global in the isolated legacy consumer as well.
    api.Q.floor_diagnostics = floor_diagnostics
    return api

def protocol(bundle, name, entry, api):
    context = _original_protocol(bundle, name, entry, api)
    files = bundle['files']; q = api.Q
    execution = q.bound(entry['execution'], files)
    Q.require(execution.get('schema') == 'r3-engineering-posttrain-execution-v1'
              and execution.get('test_read') is False
              and execution.get('scientific_acceptance') is False,
              'evaluation identity scope differs')
    spec = q.bound(execution['spec'], files)
    Q.require(files.get(execution['spec']) == execution['spec_sha256']
              and spec.get('evaluation_profile') == 'track_kt',
              'evaluation identity specification differs')
    model = entry['model']; base = model['base_path']
    Q.require(spec['model'] == base, 'scorer model differs from member/spec')
    if name.startswith('k0_'):
        Q.require(model['kind'] == 'checkpoint' and model['path'] == base
                  and spec.get('adapter') is None, 'baseline scorer adapter differs')
        adapter = None
    else:
        Q.require(model['kind'] == 'lora-adapter-unmerged', 'trained scorer kind differs')
        plan = q.bound(entry['plan'], files)
        adapter = str(Path(plan['out'])/'adapter')
        Q.require(plan['model'] == base and spec['training'] == plan['out']
                  and model['path'] == spec.get('adapter') == adapter,
                  'scorer adapter differs from training/member/spec')
    # Keep every common setting byte-for-byte in the expected protocol. The
    # unchanged report consumer compares the entire scorer dict, not a subset.
    header = copy.deepcopy(context['protocol_header'])
    Q.require(isinstance(header.get('scorer'), dict)
              and {'model_path','adapter'} <= header['scorer'].keys(),
              'common scorer identity fields absent')
    header['scorer']['model_path'] = base
    header['scorer']['adapter'] = adapter
    return dict(context, protocol_header=header)

Q.protocol = protocol
Q.source_api = source_api
for name in ('source_api','read_boundary','evaluate','main','entries','numerical','chronology',
             'member','verify_prelaunch','training_runtime','evaluation_runtime'):
    globals()[name] = getattr(Q, name)

if __name__ == '__main__':
    raise SystemExit(main())
