"""Reconstruct all seven development members from sources, never authorize tests.

Run in a fresh CPU process with the externally pinned report tool and scientific
closure. This produces engineering source evidence only: even complete evidence
cannot turn engineering training into formal eligibility or select a candidate.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


HERE = Path(__file__).resolve().parent
K = module(HERE/'r3_final_campaign.py', 'campaign_sources_structure')
M = module(HERE/'r3_model_inventory.py', 'campaign_sources_inventory')


def require(ok, message):
    if not ok: raise ValueError(message)


def safe(value):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts and str(p) == value
            and not any(x.is_symlink() for x in (p, *p.parents)), 'canonical nonsymlink path required')
    return p


def sha(path):
    path = safe(str(path)); before = path.stat()
    require(stat.S_ISREG(before.st_mode), 'nonregular source file')
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 22), b''): value.update(block)
    require(M.fingerprint(before) == M.fingerprint(path.stat()), 'source changed during hashing')
    return value.hexdigest()


def digest(value):
    return hashlib.sha256(K.canonical(value).encode()).hexdigest()


def artifact(entry):
    require(set(entry) == {'path', 'sha256'}, 'artifact descriptor differs')
    p = safe(entry['path']); K.pin(entry['sha256'])
    require(sha(p) == entry['sha256'], 'artifact changed: '+str(p))
    return json.loads(p.read_text())


def scope(report):
    h = report['header']
    require(set(h.get('partitions', [])) == {'dev', 'calibration'}
            and h.get('track_t_config') == 'r3', 'development scope required')
    require(set(h.get('stages', '').split(',')) == {'k_score', 't_score'}, 'complete development scoring required')
    require(h.get('arm') in ('K0', 'K1', 'K2', 'K1-QO', 'K1-PT'), 'unsupported member')
    require(h.get('primary_input_mode') == ('drop' if h['arm'] == 'K1-QO' else 'full'),
            'member input mode differs')
    for p in h.get('data_files', {}):
        require(Path(p).name not in ('test.jsonl', 'test.variants.jsonl'), 'test dataset in development evidence')
    return h


def source_snapshot(entry, header, kev_dir, data_root):
    """Bind all consumed source files and directory membership, without caches."""
    run = safe(entry['report']['path']).parent
    files = {str(run/name) for name in ('selection_report.json', 'SCORING_RECEIPT.track_kt.json',
                                       'RUN_IDENTITY.json', 'EVAL_COMPLETE.track_kt.json')}
    files.update(header.get('data_files', {}))
    files.update((str(Path(kev_dir)/'manifest.json'), str(Path(data_root)/'manifest.json')))
    files.update(value['path'] for value in entry.values() if value is not None)
    trees = {}
    for name in ('trackk', 'trackt', 'manifests'):
        root = safe(str(run/name)); require(root.is_dir(), 'source directory missing: '+str(root))
        members = []
        for path in sorted(root.rglob('*')):
            safe(str(path)); mode = path.stat().st_mode
            require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'nonregular source entry')
            relative = str(path.relative_to(root))
            if name == 'trackk':
                require(not any(p == 'test' or p.endswith('__test') for p in path.relative_to(root).parts),
                        'test readouts in development run')
            members.append({'path':relative, 'kind':'file' if stat.S_ISREG(mode) else 'directory'})
            if stat.S_ISREG(mode): files.add(str(path))
        trees[str(root)] = members
    model = header['model']; roots = [model['base_path']]
    if header['arm'] != 'K0':
        roots.append(model['path']); files.add(str(Path(model['path']).parent/'manifest.json'))
    for filename in files:
        path = safe(filename)
        require(path.name not in ('test.jsonl','test.variants.jsonl')
                and not ('test' in path.parts and path.suffix in ('.jsonl','.parquet')),
                'test dataset in development evidence')
    models = {p:M.capture(p) for p in sorted(set(roots))}
    for label,root in [('base_inventory', model['base_path']),
                       ('adapter_inventory', model['path'] if header['arm'] != 'K0' else None)]:
        if root is not None:
            inv = artifact(entry[label])
            require(models[root] == inv['inventory']
                    and M.identity(models[root]) == inv['inventory_sha256'],
                    'source snapshot model byte inventory differs')
    return {'files':{p:sha(p) for p in sorted(files)}, 'trees':trees, 'models':models}


def rebuild_member(entry, report_tool, deps, kev_dir, data_root, code_identity):
    """Actual model bytes and original frozen report reconstruction are required."""
    require(set(entry) == {'report', 'base_inventory', 'adapter_inventory'}, 'member source fields differ')
    stored = artifact(entry['report']); h = scope(stored)
    require(stored.get('schema') == 'r3-selection-report-v1'
            and stored.get('scientific_acceptance') is False, 'development report required')
    path = safe(entry['report']['path'])
    require(path.name == 'selection_report.json', 'selection report filename required')
    receipt_path = safe(str(path.parent/'SCORING_RECEIPT.track_kt.json'))
    receipt = json.loads(receipt_path.read_text())
    scope(receipt)
    require(receipt['header'] == h, 'receipt/report headers differ')
    for directory in ('trackk', 'trackt'):
        tree = safe(str(path.parent/directory))
        for child in tree.rglob('*'): safe(str(child))
    for readout in (path.parent/'trackk').rglob('*.jsonl'):
        require(not any(part == 'test' or part.endswith('__test')
                        for part in readout.relative_to(path.parent/'trackk').parts),
                'test readouts in development run')
    identity = h['model']; base = str(safe(identity['base_path']))
    adapter = None if h['arm'] == 'K0' else str(safe(identity['path']))
    if adapter is not None: safe(str(Path(adapter).parent/'manifest.json'))
    require(base in (K.BASE, K.INSTRUCT), '0.8B registered base required')
    inventories = {}
    for label, root in [('base_inventory', base), ('adapter_inventory', adapter)]:
        if root is None:
            require(entry[label] is None, 'K0 must not supply adapter inventory'); continue
        inv = artifact(entry[label]); M.verify(root, inv['inventory'], inv['inventory_sha256'])
        inventories[label] = inv['inventory_sha256']
    before = source_snapshot(entry, h, kev_dir, data_root)
    # Frozen legacy adapter identities omit base bytes, so the full inventory
    # above is mandatory. Compare all identity fields, not just its SHA.
    with tempfile.TemporaryDirectory(prefix='nga-campaign-identity-') as cache:
        current = deps[1].TL.model_identity(base, adapter, cache)
    fields = ('path', 'sha256', 'kind', 'base_path', 'base_revision')
    require(all(current.get(k) == identity.get(k) for k in fields), 'current model identity differs')
    actual = report_tool.rebuild(path.parent, kev_dir, data_root, deps)
    require(K.canonical(actual) == K.canonical(stored), 'saved report differs from reconstructed source')
    evidence = {'report': entry['report'], 'inventories': inventories, 'code': code_identity,
                'reconstructed_report_sha256': digest(actual), 'source_snapshot':before}
    member = {'arm': h['arm'], 'role': 'baseline' if h['arm'] == 'K0' else
              'control' if h['arm'] in ('K1-QO', 'K1-PT') else 'candidate',
              'model': {**current, 'base_inventory_sha256': inventories['base_inventory']}}
    if adapter is not None:
        training = deps[1].train_identity(actual)
        require(training['training_variant']['total_steps'] == 3116, 'full training required')
        require(all(actual['selection_evidence'].get(k) == v for k,v in training.items()),
                'stored training identity differs')
        safe(training['training_manifest'])
        member['training'] = training; evidence['training'] = training
    # Check this member now; verify() checks all members again after composition.
    artifact(entry['report'])
    if adapter is not None:
        require(sha(member['training']['training_manifest']) == member['training']['training_manifest_sha256'],
                'training manifest changed during reconstruction')
    require(source_snapshot(entry, h, kev_dir, data_root) == before,
            'member source snapshot changed during reconstruction')
    member['verified_evidence_sha256'] = digest(evidence)
    return member, evidence


def verify(spec):
    require(spec.get('schema') == 'r3-campaign-sources-request-v1', 'request schema differs')
    require(spec.get('selected_arm') in ('K1', 'K2'), 'candidate arm required')
    require(isinstance(spec.get('members'), list) and len(spec['members']) == 7, 'seven source members required')
    tool = spec['report_tool']; safe(tool['path']); K.pin(tool['sha256'])
    require(sha(tool['path']) == tool['sha256'], 'report tool changed')
    manifest_path = safe(spec['closure_manifest']['path'])
    require(manifest_path.name == 'manifest.json', 'canonical manifest.json required')
    closure = artifact(spec['closure_manifest'])
    root = manifest_path.parent
    code_root = safe(str(root/'r3_code'))
    safe(str(root/'r0_code'))
    require(code_root.resolve().parent == root.resolve(), 'canonical closure root differs')
    require(bool(closure.get('code')), 'scientific closure missing')
    kev, data = str(safe(spec['kev_dir'])), str(safe(spec['data_root']))
    code = {'report_tool': tool, 'closure_manifest': spec['closure_manifest'],
            'consumer_sha256': sha(__file__), 'structure_sha256': sha(HERE/'r3_final_campaign.py'),
            'inventory_sha256': sha(HERE/'r3_model_inventory.py')}
    R = module(tool['path'], 'campaign_sources_report_tool')
    deps = R.modules(code_root)
    members, sources = [], []
    for entry in spec['members']:
        member, evidence = rebuild_member(entry, R, deps, kev, data, code)
        members.append(member); sources.append(evidence)
    campaign = {'schema':'r3-final-campaign-v1', 'size':'0.8B',
                'selected_arm':spec['selected_arm'], 'members':members}
    structure = K.verify(campaign)
    artifact(spec['closure_manifest'])
    for entry in closure['code'].values():
        require(sha(safe(entry['snapshot'])) == entry['sha256'], 'scientific dependency changed during reconstruction')
    require(sha(tool['path']) == tool['sha256'], 'report tool changed during reconstruction')
    for entry, evidence in zip(spec['members'], sources):
        current_header = scope(artifact(entry['report']))
        require(source_snapshot(entry, current_header, kev, data) == evidence['source_snapshot'],
                'campaign source snapshot changed after member reconstruction')
    return {'schema':'r3-campaign-source-evidence-v1', 'campaign':campaign, 'structure':structure,
            'sources':sources, 'request_sha256':digest(spec), 'code':code,
            'scientific_acceptance':False, 'publication_authorized':False, 'test_read':False,
            'scope':'engineering development source reconstruction; requested arm is not a selection decision',
            'remaining':['formal training eligibility and exact-plan review',
                         'R0/PT R0 gates and real recovery evidence',
                         'final selection and independently authenticated Astra acceptance',
                         'final test execution and source-verified same-test comparison']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', required=True); p.add_argument('--sha256', required=True)
    p.add_argument('--output', required=True); a = p.parse_args()
    spec = artifact({'path':a.request, 'sha256':a.sha256})
    out = safe(a.output)
    require(out.name not in ('FINAL.json', 'report.json', 'selection_report.json'), 'reserved output name')
    result = verify(spec)
    with out.open('x') as f: f.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'output':str(out),'sha256':sha(out),'scientific_acceptance':False}))


if __name__ == '__main__': main()
