#!/usr/bin/env python3
"""Supplement existing arithmetic audits with frozen Kev checkpoint metadata bindings.

Only CPU weights_only loading is used; no native loader or metric implementation is imported.
This audits saved provenance, not the hardware execution of historical logits.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def stamp(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def verify_metadata(meta, config, environment, marker):
    require(meta['base'] == config['base_id'], 'Checkpoint base ID differs')
    require(meta['base_revision'] == config['base_revision'] == marker.splitlines()[0], 'Checkpoint base revision differs')
    t = meta.get('temperature', 1.0)
    require(type(t) in (float, int) and math.isfinite(t) and t > 0, 'Invalid checkpoint temperature')
    require(type(environment['temperature']) in (float, int) and environment['temperature'] == t,
            'Environment temperature differs from checkpoint')
    require(meta.get('weights', 'lora') == 'lora' and meta.get('weights_dtype', 'fp32') == 'fp32',
            'Unexpected checkpoint weight protocol')
    require(environment['runtime'] == config['runtime'], 'Runtime differs')
    m = environment['model']
    require(m['dtype'] == 'float32' and m['attention'] == 'eager' and m['backend'] == 'torch', 'Recorded execution protocol differs')
    return {k: meta.get(k, default) for k, default in [('base', None), ('base_revision', None),
            ('temperature', 1.0), ('weights_dtype', 'fp32'), ('weights', 'lora'), ('option_isolation', False)]}


def verify_driver(path):
    tree = ast.parse(Path(path).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'LoadOptions']
    require(len(calls) == 1, 'Ambiguous native LoadOptions calls')
    call = calls[0]
    require(not call.args and {k.arg for k in call.keywords} == {'dtype', 'attn', 'merge'}, 'Unexpected LoadOptions overrides')
    args = {k.arg: ast.unparse(k.value) for k in call.keywords}
    require(args == {'dtype': 'torch.float32', 'attn': "'eager'", 'merge': 'True'}, 'Frozen native execution options differ')
    return {'line': call.lineno, 'options': args, 'temperature_override': False,
            'limit': 'Static frozen driver invocation, not independent hardware attestation.'}


def verify_frozen(path, files):
    path = Path(path)
    require(str(path) in files, 'Required checkpoint binding dependency omitted: ' + str(path))
    h = sha(path)
    require(files[str(path)] == h, 'Frozen binding dependency changed: ' + str(path))
    return h


def release_binding(checkpoint, config, files, publication_files=None):
    # README supplies explicit release identifier and weight hash prefixes. A directory
    # name or numerical result alone cannot map a checkpoint to a publication.
    readme = checkpoint / 'README.md'
    h = verify_frozen(readme, files if str(readme) in files else (publication_files or {}))
    text = readme.read_text()
    adapters = re.findall(r'adapter sha256 `([0-9a-f]{8,64})', text)
    heads = re.findall(r'head\.pt` sha256 `([0-9a-f]{8,64})', text)
    require(len(adapters) == len(heads) == 1, 'Ambiguous published weight identities')
    require(sha(checkpoint/'adapter_model.safetensors').startswith(adapters[0]) and
            sha(checkpoint/'head.pt').startswith(heads[0]), 'Published checkpoint weight prefix differs')
    refs = set(re.findall(r'runs/release/(kev-[a-z0-9-]+)\.json', text))
    require(len(refs) == 1, 'Ambiguous published release identifier')
    release = refs.pop()
    result = {'release': release, 'readme_sha256': h, 'adapter_hash_prefix': adapters[0],
              'head_hash_prefix': heads[0], 'original_run_frozen_readme': str(readme) in files, 'scope': 'Published README hashes (prefixes where supplied); not upstream full-file byte proof.'}
    if 'release_spec' in config:
        path = Path(config['release_spec']); result['release_spec_sha256'] = verify_frozen(path, files)
        spec = load(path)
        require(spec['release'] == release, 'Wrong release spec for checkpoint')
        require(spec['drop_ids'] == config['drop_ids'], 'Release exclusion policy differs')
    else:
        result['release_spec_status'] = 'Not part of this earlier run configuration; README mapping only.'
    return result


def audit(config_path, head_loader, publication_files=None):
    config_path = Path(config_path); config_hash = sha(config_path); c = load(config_path)
    run = Path(c['out']); files = c['files']; ck = Path(c['checkpoint']); base = Path(c['base'])
    checked = {}
    for path in [ck/'head.pt', ck/'adapter_model.safetensors', ck/'adapter_config.json', base/'.complete', base/'config.json']:
        checked[str(path)] = verify_frozen(path, files)
    environment = load(run/'ENVIRONMENT.json')
    metadata = verify_metadata(head_loader(ck/'head.pt'), c, environment, (base/'.complete').read_text())
    adapter = load(ck/'adapter_config.json')
    require(adapter['base_model_name_or_path'] == c['base_id'], 'Adapter base mapping differs')
    drivers = [Path(f) for f in files if Path(f).name in ('reference_kev_eval.py', 'reference_kev_devtools.py')]
    require(len(drivers) == 1, 'Driver identity ambiguous')
    checked[str(drivers[0])] = verify_frozen(drivers[0], files)
    driver = verify_driver(drivers[0]); release = release_binding(ck, c, files, publication_files)
    identity = stamp(c)
    require(load(run/'CONFIG_RECEIPT.json') == {'stamp': identity}, 'Config receipt mismatch')
    terminal = load(run/'REFERENCE_COMPLETE.json')
    require(type(terminal.get('rc')) is int and terminal['rc'] == 0 and terminal['stamp'] == identity, 'Inference terminal failed/mismatched')
    require(set(terminal['suites']) == {s['name'] for s in c['suites']}, 'Suite terminal coverage differs')
    report = load(run/'report.json')
    require(report['stamp'] == identity and report['run_of_record'] is True and report['suite_reports'] == terminal['suites'], 'Aggregate binding differs')
    require(re.fullmatch(r'rc=0 utc=\S+\n?', (run/'DONE').read_text()) and not (run/'FAILED').exists(), 'Wrapper failed/conflicting')
    for name, binding in terminal['suites'].items():
        for field, filename in [('report_sha256', 'report.json'), ('rows_sha256', 'rows.json')]:
            require(sha(run/name/filename) == binding[field], 'Suite output binding differs')
        suite = load(run/name/'report.json')
        require(suite['native_serving_temperature'] == metadata['temperature'], 'Suite serving temperature differs')
    receipt = run/'LAUNCH_RECEIPT.json'
    launch = {'status': 'absent_in_original_run', 'scope': 'No retroactive launch identity claim'}
    if receipt.exists():
        l = load(receipt)
        require(l['config_sha256'] == config_hash and l['image'] == c['image'], 'Launch config/image binding differs')
        require(l['wrapper_sha256'] == sha(run/'run.sh'), 'Launch wrapper differs')
        launch = {'status': 'saved_receipt_bound', 'sha256': sha(receipt), 'container_id': l['container_id'],
                  'scope': 'Saved receipt binding; this supplementary tool does not inspect historical Docker state.'}
    for path, h in checked.items():
        require(sha(path) == h, 'Binding input changed during audit')
    require(sha(config_path) == config_hash, 'Config changed during audit')
    return {'status': 'CHECKPOINT_BINDING_VERIFIED_SCOPED', 'run': str(run), 'config_sha256': config_hash,
            'environment_sha256': sha(run/'ENVIRONMENT.json'), 'terminal_sha256': sha(run/'REFERENCE_COMPLETE.json'),
            'report_sha256': sha(run/'report.json'), 'metadata': metadata, 'binding_files': checked,
            'driver': driver, 'publication': release, 'launch': launch,
            'scope': 'Frozen checkpoint/base/temperature and saved output bindings. Does not re-audit metric arithmetic, authenticate historical logits or replace Astra review.'}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--config', action='append', required=True); p.add_argument('--out', required=True); p.add_argument('--publication-manifest', required=True); a = p.parse_args()
    require(len(set(map(str, map(Path, a.config)))) == len(a.config), 'Duplicate config')
    out = Path(a.out); require(not out.exists(), 'Refuse to overwrite audit report')
    os.environ['TORCH_DEVICE_BACKEND_AUTOLOAD'] = '0'
    import torch
    publication_hash = sha(a.publication_manifest); publication_files = load(a.publication_manifest)
    for path, h in publication_files.items():
        require(sha(path) == h, 'Publication supplement changed')
    results = [audit(path, lambda q: torch.load(q, map_location='cpu', weights_only=True), publication_files) for path in a.config]
    require(sha(a.publication_manifest) == publication_hash, 'Publication manifest changed')
    for path, h in publication_files.items():
        require(sha(path) == h, 'Publication supplement changed during audit')
    out.write_text(json.dumps({'status': 'CHECKPOINT_BINDINGS_VERIFIED_SCOPED', 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                              'tool_sha256': sha(__file__), 'publication_manifest_sha256': publication_hash, 'runs': results}, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': 'CHECKPOINT_BINDINGS_VERIFIED_SCOPED', 'runs': len(results), 'report_sha256': sha(out)}))

if __name__ == '__main__':
    main()
