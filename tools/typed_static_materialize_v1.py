"""Freeze reviewed Typed v2 static work before release, then rebind a fresh package.

No resource claim, no review generation, no NPU launch. A materialization config
must bind an independently accepted static manifest; self-consistent hashes alone
are not independent approval. Original runtime and its full launch verification
are unchanged. Static preparation repeats full source rendering and model checks.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import types


def need(ok, why):
    if not ok:
        raise ValueError(why)


def safe(p):
    p = Path(p)
    need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'unsafe path')
    return p


def sha(p):
    h = hashlib.sha256()
    with safe(p).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(p):
    return json.loads(safe(p).read_bytes())


def put(p, value):
    p = safe(p)
    with p.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def ref(p):
    return dict(path=str(safe(p)), sha256=sha(p))


def checked(r):
    need(set(r) == {'path', 'sha256'} and sha(r['path']) == r['sha256'], 'reference changed')
    return read(r['path'])


def module(r):
    checked_bytes = safe(r['path']).read_bytes()
    need(hashlib.sha256(checked_bytes).hexdigest() == r['sha256'], 'runtime changed')
    m = types.ModuleType('accepted_typed_runtime'); m.__file__ = r['path']
    exec(compile(checked_bytes, m.__file__, 'exec'), m.__dict__)
    return m


def copy_checked(src, dst, pin):
    need(sha(src) == pin, 'static input changed')
    dst = safe(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    with safe(src).open('rb') as f, dst.open('xb') as out:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''): out.write(block)
        out.flush(); os.fsync(out.fileno())
    need(sha(dst) == pin, 'static copy differs')


def freeze(c):
    """Expensive checks happen before any predecessor release is needed."""
    need(c['schema'] == 'typed-static-freeze-config-v1', 'freeze schema')
    d = checked(c['source_plan']); source = safe(c['source_plan']['path']).parent
    original = checked(d['config']); acceptance = checked(c['preparation_acceptance'])
    need(acceptance['verdict'] == 'PASS_CODE_AND_PREPARATION_ONLY', 'preparation review scope')
    pins = acceptance['source_and_evidence_sha256']
    need(pins.get(c['source_plan']['path']) == c['source_plan']['sha256'] and pins.get(d['config']['path']) == d['config']['sha256'], 'unreviewed source package')
    need(original['schema'] == 'typed-qwen-execution-config-v2', 'typed v2 only')
    runtime = module(original['modules']['runtime'])
    runtime.verify(c['source_plan']['path'], c['source_plan']['sha256'], model_files=True, cpu=True)
    runtime.validate_population(original)
    out = safe(c['output']); out.mkdir(exist_ok=False)
    blobs = {}
    # Copy all package-local static bytes; resource policy is deliberately excluded.
    policy = original['resources']['policy']['path']
    for path, pin in original['files'].items():
        if path == policy: continue
        need(pins.get(path) == pin, 'static file absent from accepted preparation')
        if safe(path).is_relative_to(source):
            dest = out / 'blobs' / safe(path).relative_to(source)
            copy_checked(path, dest, pin); blobs[path] = ref(dest)
        else:
            need(sha(path) == pin, 'external static input changed')
    put(out / 'SOURCE-CONFIG.json', original); put(out / 'SOURCE-PLAN.json', d)
    manifest = dict(schema='typed-static-material-v1', source_plan=c['source_plan'], source_config=d['config'],
                    preparation_acceptance=c['preparation_acceptance'], original_root=str(source),
                    config=ref(out / 'SOURCE-CONFIG.json'), plan=ref(out / 'SOURCE-PLAN.json'), blobs=blobs,
                    model_full_hash_verified=True, source_population_rerendered=True,
                    npu_launched=False, activation_authorized=False, scientific_acceptance=False)
    put(out / 'STATIC.json', manifest)
    return ref(out / 'STATIC.json')


def rebind_config(original, oldroot, newroot, chip, policy):
    """Only identity, local locations and resource policy may change."""
    need(type(chip) is int and 0 <= chip < 8, 'chip differs')
    need(re.fullmatch('[a-z0-9][a-z0-9_-]*', newroot.name), 'run name differs')
    old_policy = original['resources']['policy']['path']
    need(sha(old_policy) == original['resources']['policy']['sha256'], 'source policy changed')
    old = read(old_policy)
    removed = {old_policy} | {r['path'] for r in old.get('predecessor', {}).values()} | {r['path'] for r in old.get('priority_refs', [])}
    def relocate(v):
        if isinstance(v, dict): return {relocate(k): relocate(x) for k, x in v.items()}
        if isinstance(v, list): return [relocate(x) for x in v]
        if isinstance(v, str) and v.startswith(str(oldroot) + '/'):
            return str(newroot / Path(v).relative_to(oldroot))
        return v
    result = relocate(copy.deepcopy(original))
    result.update(run_id=newroot.name, container='nga-' + newroot.name.replace('_', '-'), output=str(newroot / 'output'))
    result['resources'].update(chip=chip, policy=ref(newroot / 'RESOURCE-POLICY.json'))
    result['files'] = {relocate(k): v for k, v in original['files'].items() if k not in removed}
    additions = [result['resources']['policy'], *policy.get('predecessor', {}).values(), *policy.get('priority_refs', [])]
    for r in additions:
        need(set(r) == {'path', 'sha256'} and sha(r['path']) == r['sha256'], 'resource reference changed')
        need(r['path'] not in result['files'] or result['files'][r['path']] == r['sha256'], 'resource/static pin conflict')
        result['files'][r['path']] = r['sha256']
    return result


def materialize(c):
    need(c['schema'] == 'typed-static-materialize-config-v1', 'materialize schema')
    m = checked(c['static_manifest'])
    need(m['schema'] == 'typed-static-material-v1' and m['model_full_hash_verified'] is True and m['source_population_rerendered'] is True, 'static validation missing')
    original = checked(m['config']); oldplan = checked(m['plan'])
    # Authenticate the previously accepted source once more, without model reload/render.
    checked(m['source_plan']); checked(m['source_config']); review = checked(m['preparation_acceptance'])
    need(review['verdict'] == 'PASS_CODE_AND_PREPARATION_ONLY', 'static review scope')
    for reference in (m['source_plan'], m['source_config']):
        need(review['source_and_evidence_sha256'].get(reference['path']) == reference['sha256'], 'static source not reviewed')
    need(oldplan['config'] == m['source_config'] and original == checked(m['source_config']), 'source projection differs')
    oldroot = safe(m['original_root']); root = safe(c['root']); need(root != oldroot, 'source output reuse')
    policy = checked(c['resource_policy'])
    need(policy.get('schema') in ('PREPARATION_ONLY_NO_RESOURCE_CLAIM','native-dataset-physical-free-v1'), 'unsupported resource policy')
    if policy['schema'] != 'PREPARATION_ONLY_NO_RESOURCE_CLAIM':
        need(policy['run'] == 'r3_runs/' + root.name and type(policy['chip']) is int and policy['chip'] == c['chip'] and policy['allocation'] == original['resources']['allocation'], 'resource policy identity differs')
        need(policy.get('scientific_acceptance') is False and policy.get('test_read') is False, 'resource policy authority')
    root.mkdir(exist_ok=False); (root / 'output').mkdir()
    for source, r in m['blobs'].items():
        need(safe(source).is_relative_to(oldroot) and original['files'].get(source) == r['sha256'], 'foreign static blob')
        copy_checked(r['path'], root / safe(source).relative_to(oldroot), r['sha256'])
    put(root / 'RESOURCE-POLICY.json', policy)
    config = rebind_config(original, oldroot, root, c['chip'], policy)
    runtime = module(config['modules']['runtime']); runtime.config_validate(config)
    for path, pin in config['files'].items(): need(sha(path) == pin, 'materialized input changed')
    put(root / 'CONFIG.json', config)
    # Derive the exact unchanged runtime projection. verify() independently checks
    # every projected field and mount; never monkeypatch population validation.
    d = copy.deepcopy(oldplan)
    for key in ('modules','population','typed','protocol','upstream','container','host_name','host_python','host_environment','cpu_python','cpu_environment','image','environment','scope','test_read','scientific_acceptance','candidate_test_authority','candidate_selection_allowed','poll_seconds'):
        d[key] = config[key]
    d.update(config=ref(root / 'CONFIG.json'), files=dict(config['files'], **{str(root / 'CONFIG.json'):sha(root / 'CONFIG.json')}),
             chip=c['chip'], queue=config['resources']['policy'], allocation=config['resources']['allocation'],
             out=config['output'], run='r3_runs/' + root.name)
    d['mounts'] = runtime.mounts(d, root / 'PLAN.json'); put(root / 'PLAN.json', d)
    runtime.verify(str(root / 'PLAN.json'), sha(root / 'PLAN.json'), model_files=False, cpu=True)
    result = dict(schema='typed-static-materialization-result-v1', status='PREPARED_NOT_ACTIVATED',
                  plan=ref(root / 'PLAN.json'), config=ref(root / 'CONFIG.json'), static_manifest=c['static_manifest'],
                  population=config['population']['count'], model=config['model']['name'],
                  resource_policy_activatable=policy.get('schema') != 'PREPARATION_ONLY_NO_RESOURCE_CLAIM',
                  npu_launched=False, activation_authorized=False, scientific_acceptance=False,
                  pending=['independent exact execution review including static manifest','unchanged launch model hash verification','locked physical resource generation checks'])
    put(root / 'PREPARATION.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['freeze','materialize']); p.add_argument('--config', required=True); p.add_argument('--sha256', required=True)
    args=p.parse_args(); need(sha(args.config)==args.sha256,'input configuration changed')
    print(json.dumps(globals()[args.mode](read(args.config))),flush=True)
